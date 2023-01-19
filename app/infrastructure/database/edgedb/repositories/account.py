from __future__ import annotations

from app import crud
from app.app.repositories import IAccountRepository
from app.domain.entities import Account


class AccountRepository(IAccountRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

    async def save(self, account: Account) -> Account:
        created_account = await crud.account.create(
            self.conn,
            username=account.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
            storage_quota=account.storage_quota,
            created_at=account.created_at,
        )
        return Account.construct(
            id=created_account.id,
            username=account.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
            storage_quota=account.storage_quota,
            created_at=account.created_at,
        )
