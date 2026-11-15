import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  apiFetch,
  apiUpload,
  mapApiError,
  type Product,
  type ProductImage,
} from "../../shared/api";
import { ProductThumb } from "../../shared/media/ProductThumb";
import { useAuthMediaUrl } from "../../shared/media/useAuthMediaUrl";
import { toPersianDigits } from "../../shared/money";
import { createIdempotentAction } from "../../shared/mutations/idempotentAction";
import { queryKeys } from "../../shared/query/keys";
import { ConfirmDialog, ErrorState } from "../../shared/ui";
import { canWriteCatalog } from "./catalogPermissions";

const MAX_IMAGES = 5;
const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

type ProductImagesDialogProps = {
  open: boolean;
  tenantId: string;
  product: Product | null;
  role: string;
  onClose: () => void;
};

function clientValidate(file: File): string | null {
  if (!ALLOWED_TYPES.has(file.type)) {
    return "فقط تصویر JPEG، PNG یا WebP پذیرفته می‌شود.";
  }
  if (file.size > MAX_BYTES) {
    return "حجم تصویر بیش از حد مجاز است.";
  }
  return null;
}

export function ProductImagesDialog({
  open,
  tenantId,
  product,
  role,
  onClose,
}: ProductImagesDialogProps) {
  const queryClient = useQueryClient();
  const titleId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canWrite = canWriteCatalog(role);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProductImage | null>(null);
  const [uploading, setUploading] = useState(false);

  const uploadAction = useMemo(() => createIdempotentAction("products.image.upload"), []);
  const primaryAction = useMemo(() => createIdempotentAction("products.image.primary"), []);
  const reorderAction = useMemo(() => createIdempotentAction("products.image.reorder"), []);
  const deleteAction = useMemo(() => createIdempotentAction("products.image.delete"), []);

  const productId = product?.id ?? "";

  const imagesQuery = useQuery({
    queryKey: queryKeys.productImages(tenantId, productId),
    queryFn: () =>
      apiFetch<ProductImage[]>(
        `/api/v1/tenants/${tenantId}/products/${productId}/images`,
      ),
    enabled: open && Boolean(tenantId && productId),
  });

  const images = useMemo(() => imagesQuery.data ?? [], [imagesQuery.data]);
  const remaining = Math.max(0, MAX_IMAGES - images.length);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setDeleteTarget(null);
    setSelectedId(null);
  }, [open, productId]);

  useEffect(() => {
    if (!images.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !images.some((i) => i.id === selectedId)) {
      const primary = images.find((i) => i.is_primary) ?? images[0];
      setSelectedId(primary?.id ?? null);
    }
  }, [images, selectedId]);

  const selected = images.find((i) => i.id === selectedId) ?? null;
  const previewPath = selected?.url ?? null;
  const preview = useAuthMediaUrl(tenantId, previewPath);

  const invalidate = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: queryKeys.productImages(tenantId, productId),
      }),
      queryClient.invalidateQueries({ queryKey: queryKeys.products(tenantId) }),
    ]);
  }, [queryClient, tenantId, productId]);

  const uploadFiles = useCallback(
    async (files: FileList | File[]) => {
      if (!canWrite || !product) return;
      setError(null);
      const list = Array.from(files);
      if (!list.length) return;
      if (list.length > remaining) {
        setError(
          `هر کالا حداکثر ۵ تصویر می‌تواند داشته باشد. ${toPersianDigits(String(remaining))} جای خالی باقی است.`,
        );
        return;
      }
      setUploading(true);
      try {
        for (const file of list) {
          const localErr = clientValidate(file);
          if (localErr) {
            setError(localErr);
            break;
          }
          const action = uploadAction.begin();
          const form = new FormData();
          form.append("file", file);
          try {
            await apiUpload<ProductImage>(
              `/api/v1/tenants/${tenantId}/products/${productId}/images`,
              form,
              {
                method: "POST",
                headers: { "Idempotency-Key": action.idempotencyKey },
              },
            );
            uploadAction.clear();
          } catch (err) {
            setError(mapApiError(err));
            break;
          }
        }
        await invalidate();
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [canWrite, product, remaining, tenantId, productId, uploadAction, invalidate],
  );

  const setPrimaryMutation = useMutation({
    mutationFn: async (imageId: string) => {
      const action = primaryAction.begin();
      await apiFetch(`/api/v1/tenants/${tenantId}/images/${imageId}/primary`, {
        method: "POST",
        headers: { "Idempotency-Key": action.idempotencyKey },
        body: JSON.stringify({}),
      });
    },
    onSuccess: async () => {
      primaryAction.clear();
      setError(null);
      await invalidate();
    },
    onError: (err) => setError(mapApiError(err)),
  });

  const reorderMutation = useMutation({
    mutationFn: async (orderedIds: string[]) => {
      const action = reorderAction.begin();
      await apiFetch(`/api/v1/tenants/${tenantId}/products/${productId}/images/reorder`, {
        method: "POST",
        headers: { "Idempotency-Key": action.idempotencyKey },
        body: JSON.stringify({ image_ids: orderedIds }),
      });
    },
    onSuccess: async () => {
      reorderAction.clear();
      setError(null);
      await invalidate();
    },
    onError: (err) => setError(mapApiError(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: async (imageId: string) => {
      const action = deleteAction.begin();
      await apiFetch(`/api/v1/tenants/${tenantId}/images/${imageId}`, {
        method: "DELETE",
        headers: { "Idempotency-Key": action.idempotencyKey },
      });
    },
    onSuccess: async () => {
      deleteAction.clear();
      setDeleteTarget(null);
      setError(null);
      await invalidate();
    },
    onError: (err) => setError(mapApiError(err)),
  });

  function moveImage(imageId: string, direction: -1 | 1) {
    const idx = images.findIndex((i) => i.id === imageId);
    if (idx < 0) return;
    const next = idx + direction;
    if (next < 0 || next >= images.length) return;
    const ordered = images.map((i) => i.id);
    const tmp = ordered[idx]!;
    ordered[idx] = ordered[next]!;
    ordered[next] = tmp;
    void reorderMutation.mutateAsync(ordered);
  }

  const busy =
    uploading ||
    setPrimaryMutation.isPending ||
    reorderMutation.isPending ||
    deleteMutation.isPending;

  return (
    <>
      <Dialog
        open={open}
        onClose={busy ? undefined : onClose}
        fullWidth
        maxWidth="sm"
        aria-labelledby={titleId}
      >
        <DialogTitle id={titleId}>
          تصاویر کالا
          {product ? ` — ${product.title}` : ""}
        </DialogTitle>
        <DialogContent dividers>
          {error ? <ErrorState message={error} /> : null}

          {imagesQuery.isPending ? (
            <Stack alignItems="center" sx={{ py: 4 }}>
              <CircularProgress size={28} />
            </Stack>
          ) : imagesQuery.isError ? (
            <ErrorState
              message={mapApiError(imagesQuery.error)}
              onRetry={() => void imagesQuery.refetch()}
            />
          ) : (
            <Stack spacing={2}>
              <Box
                sx={{
                  width: "100%",
                  aspectRatio: "4 / 3",
                  borderRadius: 1,
                  bgcolor: "action.hover",
                  border: 1,
                  borderColor: "divider",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                }}
              >
                {preview.url && !preview.isError ? (
                  <Box
                    component="img"
                    src={preview.url}
                    alt={product?.title ?? "تصویر کالا"}
                    sx={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                  />
                ) : (
                  <Typography color="text.secondary">بدون تصویر</Typography>
                )}
              </Box>

              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                {images.map((img) => {
                  const selectedSx =
                    img.id === selectedId
                      ? { outline: 2, outlineColor: "primary.main", outlineOffset: 2 }
                      : {};
                  return (
                    <Box
                      key={img.id}
                      component="button"
                      type="button"
                      onClick={() => setSelectedId(img.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedId(img.id);
                        }
                      }}
                      aria-label={product?.title ?? "تصویر"}
                      aria-pressed={img.id === selectedId}
                      sx={{
                        p: 0,
                        border: "none",
                        background: "none",
                        cursor: "pointer",
                        borderRadius: 1,
                        ...selectedSx,
                      }}
                    >
                      <ProductThumb
                        tenantId={tenantId}
                        srcPath={img.thumbnail_url}
                        alt={product?.title ?? "تصویر"}
                        size={56}
                      />
                    </Box>
                  );
                })}
              </Stack>

              {canWrite && selected ? (
                <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
                  <IconButton
                    aria-label="تصویر اصلی"
                    color={selected.is_primary ? "warning" : "default"}
                    disabled={busy || selected.is_primary}
                    onClick={() => void setPrimaryMutation.mutateAsync(selected.id)}
                  >
                    {selected.is_primary ? <StarIcon /> : <StarBorderIcon />}
                  </IconButton>
                  <IconButton
                    aria-label="جابه‌جایی به بالا"
                    disabled={busy || images[0]?.id === selected.id}
                    onClick={() => moveImage(selected.id, -1)}
                  >
                    <KeyboardArrowUpIcon />
                  </IconButton>
                  <IconButton
                    aria-label="جابه‌جایی به پایین"
                    disabled={busy || images[images.length - 1]?.id === selected.id}
                    onClick={() => moveImage(selected.id, 1)}
                  >
                    <KeyboardArrowDownIcon />
                  </IconButton>
                  <IconButton
                    aria-label="حذف تصویر"
                    color="error"
                    disabled={busy}
                    onClick={() => setDeleteTarget(selected)}
                  >
                    <DeleteOutlineIcon />
                  </IconButton>
                </Stack>
              ) : null}

              {canWrite ? (
                <Box
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    if (e.dataTransfer.files?.length) {
                      void uploadFiles(e.dataTransfer.files);
                    }
                  }}
                  sx={{
                    border: 2,
                    borderStyle: "dashed",
                    borderColor: dragOver ? "primary.main" : "divider",
                    borderRadius: 1,
                    p: 2,
                    textAlign: "center",
                    bgcolor: dragOver ? "action.selected" : "transparent",
                  }}
                >
                  <CloudUploadOutlinedIcon color="action" sx={{ mb: 1 }} />
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    فایل را اینجا رها کنید یا انتخاب کنید. باقی‌مانده:{" "}
                    {toPersianDigits(String(remaining))} از{" "}
                    {toPersianDigits(String(MAX_IMAGES))}
                  </Typography>
                  <Button
                    variant="outlined"
                    component="label"
                    disabled={busy || remaining <= 0}
                    startIcon={
                      uploading ? <CircularProgress size={16} /> : <CloudUploadOutlinedIcon />
                    }
                  >
                    بارگذاری تصویر
                    <input
                      ref={fileInputRef}
                      hidden
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      onChange={(e) => {
                        if (e.target.files) void uploadFiles(e.target.files);
                      }}
                    />
                  </Button>
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  مشاهده تصاویر (فقط خواندنی)
                </Typography>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>
            بستن
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="حذف تصویر"
        description="آیا از حذف این تصویر مطمئن هستید؟ این عمل قابل بازگشت نیست."
        confirmLabel="حذف تصویر"
        confirmColor="error"
        confirming={deleteMutation.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) void deleteMutation.mutateAsync(deleteTarget.id);
        }}
      />
    </>
  );
}
