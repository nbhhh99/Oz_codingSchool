"""ai_analysis_results: (record_id, ai_model) 캐시 인덱스를 UNIQUE 로 변경

Revision ID: d4e5f6a7b8c9
Revises: c7f1a2d3b4e5
Create Date: 2026-09-04 15:40:00.000000

9일차 - AI 작업 워커 분리 반영:
- 추론을 별도 워커로 분리하면서 같은 (record_id, ai_model) 요청이 동시에
  들어올 수 있다. FastAPI 쪽 Redis 잠금으로 직렬화하지만, 잠금을 우회하는
  경합에도 결과가 한 행만 남도록 캐시 조회용 복합 인덱스를 UNIQUE 로 바꾼다.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c7f1a2d3b4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_ai_analysis_results_record_id_ai_model"
TABLE_NAME = "ai_analysis_results"
COLUMNS = ["record_id", "ai_model"]


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    op.create_index(INDEX_NAME, TABLE_NAME, COLUMNS, unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    op.create_index(INDEX_NAME, TABLE_NAME, COLUMNS, unique=False)
