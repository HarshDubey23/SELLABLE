@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================================================
echo   SELLABLE - push the update to GitHub
echo ========================================================================
echo.
echo   This adds 11 new commits on top of the 100 you already have.
echo   Your existing history is NOT rewritten and NOT deleted.
echo   Nothing is force-pushed.
echo.

REM ---------------------------------------------------------------- checks
if not exist ".git" (
  echo [ERROR] This script must sit inside your SELLABLE repository folder.
  echo         Expected to find a .git directory here: %CD%
  goto :fail
)
if not exist "SELLABLE-update.bundle" (
  echo [ERROR] SELLABLE-update.bundle is missing from this folder.
  goto :fail
)

git --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] git is not on your PATH. Open "Git Bash" or install Git for Windows.
  goto :fail
)

echo [1/6] Current state
for /f %%i in ('git rev-list --count HEAD') do set BEFORE=%%i
echo       commits right now: !BEFORE!
git log --oneline -1
echo.

REM ------------------------------------------------- safety net: backup ref
echo [2/6] Making a safety backup of your current branch
git branch -f backup-before-update HEAD
if errorlevel 1 goto :fail
echo       saved as branch: backup-before-update
echo       (if anything goes wrong: git reset --hard backup-before-update)
echo.

REM ----------------------------------------------- stash uncommitted work
echo [3/6] Setting aside any uncommitted changes
git stash push -u -m "before-sellable-update" >nul 2>&1
if errorlevel 1 (
  echo       nothing to stash
) else (
  echo       stashed - restore later with: git stash pop
)
echo.

REM ----------------------------------------------------- fetch the bundle
echo [4/6] Reading the new commits out of the bundle
git fetch "%CD%\SELLABLE-update.bundle" main
if errorlevel 1 (
  echo [ERROR] Could not read the bundle.
  goto :fail
)

git merge-base --is-ancestor HEAD FETCH_HEAD
if errorlevel 1 (
  echo.
  echo [STOP] Your current commit is NOT an ancestor of the update.
  echo        That means you have local commits the update does not contain,
  echo        and continuing would drop them.
  echo.
  echo        Nothing has been changed. Your work is safe.
  echo        Send this message back and it can be merged properly instead.
  goto :fail
)
echo       fast-forward confirmed - none of your commits are dropped
echo.

REM -------------------------------------------------------- move the branch
echo [5/6] Moving main to the updated history
git checkout main
if errorlevel 1 goto :fail
git reset --hard FETCH_HEAD
if errorlevel 1 goto :fail

for /f %%i in ('git rev-list --count HEAD') do set AFTER=%%i
echo       commits now: !AFTER!  (was !BEFORE!)
echo.

REM ---------------------------------------------------------------- push
echo [6/6] Pushing to GitHub
echo       If a login window appears, sign in as HarshDubey23.
echo.
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] The push failed - see the message above.
  echo         Common cause: not signed in. Run this and try again:
  echo             git credential-manager github login
  echo         Your local repository is already updated either way.
  goto :fail
)

echo.
echo ========================================================================
echo   DONE
echo ========================================================================
echo.
echo   github.com/HarshDubey23/SELLABLE now has !AFTER! commits.
echo.
echo   Next:
echo     1. python run.py            - should print RESULT PASS
echo     2. open http://localhost:8000/
echo     3. docs\submission\FORM_ANSWERS.md has two ">>> FILL THIS IN" markers
echo        - the institution field matters for eligibility
echo.
echo   You can delete SELLABLE-update.bundle and this .bat file now.
echo.
pause
exit /b 0

:fail
echo.
echo ========================================================================
echo   STOPPED - nothing was pushed
echo ========================================================================
echo.
pause
exit /b 1
