# Verification model

Each published target has four independent checks:

1. The working source is the earliest dated rollback copy made before that
   bundle's texture work.
2. The target is the currently installed bundle already accepted by the local
   Unity asset verifier.
3. The release builder records source, target, and patch SHA-256 hashes and
   rebuilds the target from the source plus `.f4kp` data.
4. The PowerShell installer verifies the same hashes before and after the
   staged replacement and restores its backup if the batch fails.

Texture package verification also reopens each serialized Unity bundle and
checks the intended Texture2D IDs, dimensions, formats, sampler state, full
13-level mip chains, and compressed readback quality. The catalog currently
records these as offline verification; in-game appearance still depends on the
game shader, lighting, animation, and camera distance.
