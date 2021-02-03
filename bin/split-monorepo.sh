#!/usr/bin/env bash

set -euxo pipefail

REPO="${REPO:-fruits}"
REPO_SUBDIR="${REPO_SUBDIR:-apple}"
REPO_ORIGIN_REMOTE_URL="$(git --work-tree ${REPO} --git-dir ${REPO}/.git remote get-url origin)"
SUBREPO="${SUBREPO:-fruits-apple}"
SUBREPO_BRANCHES="${SUBREPO_BRANCHES:-feature/apple-variants}"
GIT_EMAIL="${GIT_EMAIL:-massimiliano.giovagnoli.1992@gmail.com}"
GIT_NAME="${GIT_NAME:-\"Massimiliano Giovagnoli\"}"

git clone "${REPO}" "${SUBREPO}"
pushd "${SUBREPO}"
  for branch in "${SUBREPO_BRANCHES}"; do \
  	git branch -t $branch;
  done
  git remote rm origin
  git filter-branch --tag-name-filter cat --prune-empty --subdirectory-filter "${REPO_SUBDIR}" -- --all
  git reset --hard
  git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d
  git reflog expire --expire=now --all
  git gc --aggressive --prune=now
  git config user.email "${GIT_EMAIL}"
  git config user.name "${GIT_NAME}"
  git remote add origin "${REPO_ORIGIN_REMOTE_URL/cloud/orchestration}"
popd
