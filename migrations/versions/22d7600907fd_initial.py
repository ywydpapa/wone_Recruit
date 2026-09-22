# 베이스라인: 기존 DB 스키마 기준점 (init_db.py로 생성된 상태)
# 실제 테이블 생성은 init_db.py가 담당, 여기는 마이그레이션 시작점만 표시

from alembic import op
import sqlalchemy as sa

revision = '22d7600907fd'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
