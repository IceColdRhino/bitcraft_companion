# GitHub Actions CI/CD Pipeline

This repository uses GitHub Actions to automate testing, building, and releasing BitCraft Companion based on version changes in `pyproject.toml`.

## Workflow Overview

### 🔍 Pull Request Workflow (`pr-checks.yml`)

Runs on every pull request to the `dev` branch and performs:

1. **Version Check** 
   - Compares `pyproject.toml` version in PR vs `dev` branch
   - **BLOCKS merge if version is not updated**
   - Validates semantic versioning format (x.y.z)
   - Ensures version only increases

2. **Test Suite** 
   - Runs all 120+ tests using `poetry run pytest`
   - Must pass before merge is allowed

3. **Build Test** 
   - Tests executable build process without releasing
   - Validates PyInstaller configuration

**Result**: No merge possible without version bump + passing tests!

### Dev Validation Workflow (`dev-validation.yml`)

Triggers on push to `dev` branch (after PR merge) and performs:

1. **Test Validation** 
   - Re-runs full test suite to ensure merge didn't break anything
   - Validates build process without creating release
   - Confirms dev branch is stable

2. **Build Testing**
   - Tests executable generation
   - Validates PyInstaller configuration

### Release Workflow (`release.yml`)

Triggers on push to `master` branch and performs:

1. **Version Extraction**
   - Reads version from `pyproject.toml`
   - Creates release tag (e.g., `v0.2.15`)
   - Checks for duplicate releases

2. **Test Validation**
   - Re-runs full test suite to ensure merge integrity

3. **Executable Build**
   - Builds Windows executable using PyInstaller
   - Creates versioned filename (e.g., `BitCraft_Companion-v0.2.15.exe`)

4. **GitHub Release**
   - Creates tagged release with automated changelog
   - Uploads executable as downloadable asset
   - Generates release notes from commit history

## Branch Protection Setup

To enable this workflow, configure branch protection rules:

### For `dev` Branch

1. **Protect this branch** 
2. **Require a pull request before merging** 
3. **Require status checks to pass before merging** 
   - `Verify Version Bump`
   - `Run Tests`
   - `Test Build Process`
4. **Require branches to be up to date before merging** 
5. **Restrict pushes that create files** 

### For `master` Branch
1. **Protect this branch** 
2. **Require a pull request before merging** 
3. **Restrict pushes that create files** 
4. **Require review from code owners** (recommended)

### Optional Settings (Both Branches)
- **Require review from code owners**
- **Dismiss stale reviews when new commits are pushed**
- **Require linear history**

## Usage Guide

### For Feature Development

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Update Version in pyproject.toml**
   ```toml
   [tool.poetry]
   version = "0.2.16"  # Increment from current version
   ```

3. **Develop & Test Locally**
   ```bash
   poetry run pytest  # Ensure tests pass
   ```

4. **Create Pull Request to Dev**
   - PR to `dev` branch
   - GitHub Actions will automatically:
     -  Verify version was bumped
     -  Run full test suite
     -  Test build process

5. **Merge to Dev**
   - All checks must pass before merge button is enabled
   - Upon merge to dev: validation tests run (no release)

6. **Release Process** (when ready)
   - Create PR from `dev` → `master`
   - Merge to master triggers automatic release creation

### Version Bumping Strategy

Follow semantic versioning:
- **Patch** (0.2.15 → 0.2.16): Bug fixes, small improvements
- **Minor** (0.2.15 → 0.3.0): New features, functionality additions  
- **Major** (0.2.15 → 1.0.0): Breaking changes, major releases

### Development & Release Process

**Two-Stage Pipeline** 
```
Feature Branch (v0.2.16) 
  ↓ PR → dev
Version Check  + Tests  + Build Test 
  ↓ Merge to dev
Dev Validation  (tests + build check, no release)
  ↓ When ready for release
PR dev → master
  ↓ Merge to master  
Auto Release v0.2.16
  ↓ 
GitHub Release + Downloadable .exe
```

## Troubleshooting

### "Version not updated" Error
```
VERSION CHECK FAILED
Version must be updated in pyproject.toml before merging
```
**Solution**: Increment version in `pyproject.toml` before creating PR.

### "Tests failed" Error
```
Tests failed! Please fix failing tests before merge.
```
**Solution**: Run `poetry run pytest` locally and fix failing tests.

### "Tag already exists" Error
```
Tag v0.2.15 already exists!
```
**Solution**: Version was already released. Increment to next version.

### "Build failed" Error
```
Build test failed - no executable generated
```
**Solution**: Check PyInstaller configuration in `bitcraft_companion.spec`.

## Monitoring

- **Actions Tab**: View all workflow runs and their status
- **Releases Page**: See all published releases with download links
- **Pull Requests**: Check status of version/test validations

## Benefits

 **No manual releases** - Push to dev = automatic release  
 **Quality gates** - Tests must pass before merge and release  
 **Version consistency** - Single source of truth in pyproject.toml  
 **Audit trail** - Clear history of what was released when  
 **Zero config** - Fully automated pipeline  
 **Error prevention** - Cannot merge/release without proper version bump

This ensures every release represents real changes and eliminates "building exe's with issues"!