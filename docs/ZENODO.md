# Zenodo DOI Integration Guide

This guide explains how to mint a DOI for OpenAtoms releases using Zenodo.

## 1) Prerequisites
- A public GitHub repository with release tags (for example: `v0.2.0`).
- Maintainer access to repository settings.
- A Zenodo account.

## 2) Connect GitHub to Zenodo
1. Sign in to [Zenodo](https://zenodo.org/).
2. Open **Account -> GitHub**.
3. Authorize Zenodo to access your GitHub account.
4. In Zenodo repository list, enable archiving for `abdulrahimiqbal/OpenAtoms`.

## 3) Configure Metadata in Repo
- `.zenodo.json`: machine-readable deposition metadata used by Zenodo.
- `CITATION.cff`: citation metadata displayed by GitHub and tools.

Update these files before every release:
- `version`
- `publication_date`
- contributors/authors
- keywords and description

## 4) Mint DOI from a Release Tag
1. Create and push a semantic tag: `git tag -a vX.Y.Z -m "OpenAtoms vX.Y.Z"` and `git push origin vX.Y.Z`.
2. Create a GitHub release from that tag.
3. Zenodo will archive the release automatically and mint:
   - Version-specific DOI (immutable release)
   - Concept DOI (all versions)

## 5) Add DOI Badge to README
After Zenodo mints the DOI, add badge/link in `README.md`:

```markdown
[![DOI](https://zenodo.org/badge/DOI/<version-doi>.svg)](https://doi.org/<version-doi>)
```

Also update the citation section with the DOI.

## 6) Verify
- Check Zenodo record includes the correct version and metadata.
- Confirm `CITATION.cff` and README citation match the minted DOI.
- Confirm GitHub release assets are attached and downloadable.
