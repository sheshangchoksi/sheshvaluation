"""
Argon2 password hashing — winner of the Password Hashing Competition,
tunable for time/memory cost, the current recommended default over
bcrypt/pbkdf2.
"""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_hasher = PasswordHasher()

# A syntactically-valid but unusable hash, used to burn roughly the same
# CPU time on a nonexistent-email login attempt as a real one — so
# response timing doesn't reveal whether an email is registered.
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MDAwMDAwMDAwMDAwMDAwMDAwMDAwMA$MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA"


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHash:
        return False
