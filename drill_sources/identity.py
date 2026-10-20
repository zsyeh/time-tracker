import hashlib


def child_fingerprint(source_fingerprint, key):
    return hashlib.sha256(f'ucas-source-index:v1:{source_fingerprint}:{key}'.encode()).hexdigest()
