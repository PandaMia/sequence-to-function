"""Manage encrypted local secrets for STF deployments."""

from __future__ import annotations

import argparse
import json
from getpass import getpass
from pathlib import Path

from cryptography.fernet import Fernet


def generate_key() -> None:
    print(Fernet.generate_key().decode("utf-8"))


def encrypt(args: argparse.Namespace) -> None:
    key = args.key or getpass("Fernet key: ").strip()
    secrets: dict[str, str] = {}

    for name in args.secret:
        value = getpass(f"{name}: ").strip()
        if value:
            secrets[name] = value

    if not secrets:
        raise SystemExit("No secrets were provided.")

    payload = json.dumps(secrets, ensure_ascii=False, sort_keys=True).encode("utf-8")
    encrypted = Fernet(key.encode("utf-8")).encrypt(payload)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encrypted)
    output_path.chmod(0o600)
    print(f"Wrote encrypted secrets to {output_path}")


def decrypt(args: argparse.Namespace) -> None:
    key = args.key or getpass("Fernet key: ").strip()
    encrypted = Path(args.input).read_bytes()
    decrypted = Fernet(key.encode("utf-8")).decrypt(encrypted)
    parsed = json.loads(decrypted.decode("utf-8"))
    print(json.dumps(sorted(parsed.keys()), ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage encrypted STF secrets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("generate-key", help="Print a new Fernet encryption key.")

    encrypt_parser = subparsers.add_parser("encrypt", help="Create an encrypted secrets file.")
    encrypt_parser.add_argument("--output", required=True, help="Encrypted output file path.")
    encrypt_parser.add_argument("--secret", action="append", default=["OPENAI_KEY"], help="Secret name to prompt for.")
    encrypt_parser.add_argument("--key", help="Fernet key. Omit to enter it interactively.")

    decrypt_parser = subparsers.add_parser("check", help="Verify an encrypted secrets file and list secret names.")
    decrypt_parser.add_argument("--input", required=True, help="Encrypted secrets file path.")
    decrypt_parser.add_argument("--key", help="Fernet key. Omit to enter it interactively.")

    args = parser.parse_args()
    if args.command == "generate-key":
        generate_key()
    elif args.command == "encrypt":
        encrypt(args)
    elif args.command == "check":
        decrypt(args)


if __name__ == "__main__":
    main()
