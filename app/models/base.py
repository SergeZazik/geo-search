from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Every searchable table keeps the name in these columns: the local name and translations.
NAME_COLUMNS = ("name", "name_uk", "name_en", "name_ru")
# Fuzzy search by name in any language. A multicolumn GIN index serves
# conditions on any subset of its columns equally well.
NAMES_TRGM_OPS = dict.fromkeys(NAME_COLUMNS, "gin_trgm_ops")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
