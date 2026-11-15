import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import { Box } from "@mui/material";
import { useState } from "react";
import { useAuthMediaUrl } from "./useAuthMediaUrl";

const SIZE = 40;

type ProductThumbProps = {
  tenantId: string;
  /** Relative API path e.g. /api/v1/tenants/.../thumbnail — or null for placeholder. */
  srcPath?: string | null;
  alt: string;
  size?: number;
  /** When true, thumb is decorative (next to visible product name); avoid extra accessible names. */
  decorative?: boolean;
};

function Placeholder({
  size,
  alt,
  decorative,
}: {
  size: number;
  alt: string;
  decorative?: boolean;
}) {
  return (
    <Box
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : alt}
      aria-hidden={decorative ? true : undefined}
      sx={{
        width: size,
        height: size,
        borderRadius: 1,
        bgcolor: "action.hover",
        border: 1,
        borderColor: "divider",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "text.disabled",
      }}
    >
      <ImageOutlinedIcon sx={{ fontSize: size * 0.45 }} aria-hidden />
    </Box>
  );
}

/** Fixed-size product thumbnail; never shows a broken-image icon. */
export function ProductThumb({
  tenantId,
  srcPath,
  alt,
  size = SIZE,
  decorative = false,
}: ProductThumbProps) {
  const { url, isError } = useAuthMediaUrl(tenantId, srcPath);
  const [broken, setBroken] = useState(false);

  if (!srcPath || isError || broken || !url) {
    return <Placeholder size={size} alt={alt} decorative={decorative} />;
  }

  return (
    <Box
      component="img"
      src={url}
      alt={decorative ? "" : alt}
      aria-hidden={decorative ? true : undefined}
      loading="lazy"
      onError={() => setBroken(true)}
      sx={{
        width: size,
        height: size,
        borderRadius: 1,
        objectFit: "cover",
        flexShrink: 0,
        bgcolor: "action.hover",
        border: 1,
        borderColor: "divider",
        display: "block",
      }}
    />
  );
}
