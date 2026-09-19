from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from app.config import settings
url=settings.database_url
if url.startswith('postgres://'): url='postgresql+asyncpg://'+url[11:]
elif url.startswith('postgresql://'): url='postgresql+asyncpg://'+url[13:]
engine=create_async_engine(url,pool_pre_ping=True)
Session=async_sessionmaker(engine,expire_on_commit=False,class_=AsyncSession)
