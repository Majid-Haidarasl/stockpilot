"""Public contract for the catalog module.

Product images (Phase 4.5):
- HTTP and Run 6 bulk import share ProductImageService.add_prepared /
  prepare_image in adapters.outbound.image_service.
- Run 6 should resolve SKU via CatalogRepository.get_product_by_sku, then
  call prepare_image + add_prepared inside a UnitOfWork. Do not invent a
  second encode/storage path.
"""

from stockpilot.modules.catalog.adapters.outbound.image_service import (
    ImageServiceError,
    PreparedImage,
    ProductImageService,
    prepare_image,
)
from stockpilot.modules.catalog.adapters.outbound.repo import CatalogRepository

__all__ = [
    "CatalogRepository",
    "ImageServiceError",
    "PreparedImage",
    "ProductImageService",
    "prepare_image",
]
