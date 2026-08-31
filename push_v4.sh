#!/bin/bash

# Historical V4 release helper — intentionally disabled.
#
# The previous implementation deleted Git lock files, staged every file and
# force-pushed main plus historical branches. That behavior is unsafe for a
# shared, cross-machine repository and must not be restored or executed.

set -eu

echo "push_v4.sh 已停用：请使用普通分支、显式 git add 和非强制 push。" >&2
echo "先阅读 docs/PROJECT-STATE.md 与最新 docs/handoff/。" >&2
exit 2
