import argparse
import asyncio
import getpass
import sys
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.auth import hash_admin_password
from src.auth import generate_api_key
from src.database import AsyncSessionLocal, async_engine
from src.models import ReaderPartner, ReaderPartnerKey


async def create_partner(db: AsyncSession, name: str) -> ReaderPartner:
    partner = ReaderPartner(name=name)
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return partner


async def mint_key(db: AsyncSession, partner_id: uuid.UUID) -> tuple[ReaderPartnerKey, str]:
    partner = (
        await db.execute(select(ReaderPartner).where(ReaderPartner.partner_id == partner_id))
    ).scalar_one_or_none()
    if partner is None:
        raise ValueError(f"Partner not found: {partner_id}")

    raw_key, key_prefix, key_hash = generate_api_key()
    key = ReaderPartnerKey(
        partner_id=partner.partner_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key, raw_key


async def list_keys(db: AsyncSession, partner_id: uuid.UUID | None) -> list[ReaderPartnerKey]:
    stmt = select(ReaderPartnerKey).order_by(ReaderPartnerKey.created_at.asc())
    if partner_id is not None:
        stmt = stmt.where(ReaderPartnerKey.partner_id == partner_id)
    return list((await db.execute(stmt)).scalars().all())


async def revoke_key(db: AsyncSession, key_id: uuid.UUID) -> ReaderPartnerKey:
    key = (
        await db.execute(select(ReaderPartnerKey).where(ReaderPartnerKey.key_id == key_id))
    ).scalar_one_or_none()
    if key is None:
        raise ValueError(f"Key not found: {key_id}")
    if key.revoked_at is None:
        await db.execute(
            update(ReaderPartnerKey)
            .where(ReaderPartnerKey.key_id == key_id, ReaderPartnerKey.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await db.commit()
        await db.refresh(key)
    return key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Reader API partners and bearer keys.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_create = subparsers.add_parser("create-partner", help="Create a new ingest partner.")
    p_create.add_argument("--name", required=True, help="Human-readable partner name.")

    p_mint = subparsers.add_parser("mint-key", help="Mint a new API key for an existing partner.")
    p_mint.add_argument("--partner-id", required=True, type=uuid.UUID, help="Partner UUID.")

    p_list = subparsers.add_parser("list-keys", help="List API keys and their status.")
    p_list.add_argument("--partner-id", type=uuid.UUID, default=None, help="Optional partner UUID filter.")

    p_revoke = subparsers.add_parser("revoke-key", help="Revoke an API key by UUID.")
    p_revoke.add_argument("--key-id", required=True, type=uuid.UUID, help="Key UUID.")

    p_hash = subparsers.add_parser(
        "hash-admin-password",
        help="Generate a scrypt hash for READER_ADMIN_PASSWORD_HASH.",
    )
    p_hash.add_argument(
        "--password",
        default=None,
        help="Plaintext password to hash (prompts interactively if omitted).",
    )

    return parser


async def _run(args: argparse.Namespace) -> int:
    try:
        async with AsyncSessionLocal() as db:
            if args.command == "create-partner":
                partner = await create_partner(db, args.name)
                print(f"partner_id={partner.partner_id} name={partner.name}")
            elif args.command == "mint-key":
                key, raw_key = await mint_key(db, args.partner_id)
                print(f"key_id={key.key_id} key_prefix={key.key_prefix}")
                print(f"api_key={raw_key}")
                print("Store this API key now; it will not be displayed again.", file=sys.stderr)
            elif args.command == "list-keys":
                keys = await list_keys(db, args.partner_id)
                for key in keys:
                    state = "revoked" if key.revoked_at is not None else "active"
                    revoked = key.revoked_at.isoformat() if key.revoked_at is not None else "-"
                    print(
                        f"key_id={key.key_id} partner_id={key.partner_id} prefix={key.key_prefix} "
                        f"status={state} created_at={key.created_at.isoformat()} revoked_at={revoked}"
                    )
            elif args.command == "revoke-key":
                key = await revoke_key(db, args.key_id)
                print(f"revoked key_id={key.key_id} revoked_at={key.revoked_at}")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        await async_engine.dispose()


def _hash_admin_password_command(password_arg: str | None) -> int:
    password = password_arg
    if password is None:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        return 1
    print(hash_admin_password(password))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "hash-admin-password":
        return _hash_admin_password_command(args.password)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
