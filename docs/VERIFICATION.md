# Verification model

Each published target has four independent checks:

1. The authoritative live inventory identifies a verified upgrade and its
   current installed SHA-256.
2. A unique chain of `installed_and_readback_verified` journals must connect
   that same target SHA-256 back to an independently retained pristine source.
   The source hash must be attested by the matching artifact verification, or
   match the root of the successful journal chain.
3. The release builder re-hashes the live target and pristine rollback source,
   records every lineage edge, unions the changed Texture2D proof across the
   chain, then rebuilds the final target from the source plus `.f4kp` data.
4. The PowerShell installer verifies the same hashes before and after the
   staged replacement and restores its backup if the batch fails.

Texture package verification also reopens each serialized Unity bundle and
checks the intended Texture2D IDs, dimensions, formats, sampler state, full
13-level mip chains, and compressed readback quality. The catalog currently
records these as offline verification; in-game appearance still depends on the
game shader, lighting, animation, and camera distance.
