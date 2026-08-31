"""ai_analysis_results: heatmap_url nullable 변경 및 캐시 조회용 복합 인덱스 추가

Revision ID: c7f1a2d3b4e5
Revises: 940fb4c25015
Create Date: 2026-08-31 16:30:00.000000

폐렴 예측 API(REQ-PRED-001/002) 반영:
- heatmap_url: 히트맵 생성은 이후 단계이므로 선택 사항 → nullable=True
- (record_id, ai_model) 복합 인덱스: 캐시 조회 성능 (NFR-PRED-002)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c7f1a2d3b4e5"
down_revision: Union[str, Sequence[str], None] = "940fb4c25015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_ai_analysis_results_record_id_ai_model"


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "ai_analysis_results",
        "heatmap_url",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.create_index(
        INDEX_NAME,
        "ai_analysis_results",
        ["record_id", "ai_model"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX_NAME, table_name="ai_analysis_results")
    op.alter_column(
        "ai_analysis_results",
        "heatmap_url",
        existing_type=sa.String(length=255),
        nullable=False,
    )
