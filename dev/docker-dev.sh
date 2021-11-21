#!/bin/bash

# Determine SCRIPT_DIR
[ -z "$SHELL" ] && SHELL=/bin/bash
case $(basename $SHELL) in
	zsh)
		SCRIPT_DIR=$(dirname $0:A)
		;;

	*)
		SCRIPT_DIR=$(cd $(dirname $0); pwd)
		;;
esac

# Make SCRIPT_DIR absolute
SCRIPT_DIR="$(cd "$SCRIPT_DIR"; pwd -P)"
cd "$SCRIPT_DIR"

# Read site config
. $SCRIPT_DIR/site.conf

# Check if a rebuild is needed
if which md5sum >/dev/null; then
  TAG=$(cat Dockerfile requirements.txt scripts/docker_* |md5sum |cut -d ' ' -f 1)
else
  echo "WARNING: md5sum command not found. You may need to manually rebuild with -b"
  TAG=latest
fi
echo "Image Tag: $TAG"

IMAGE="${SITE_NAME}-automation:$TAG"
HIST_FILE="$SCRIPT_DIR/.docker-dev-zsh_history"

[ -z "$(docker images -q $IMAGE 2> /dev/null)" ] && BUILD_IMAGE=y
[[ "$1" == '-b' ]] && BUILD_IMAGE=y
if [ -n "$BUILD_IMAGE" ]; then
  cd $SCRIPT_DIR
  docker build -t "$IMAGE" .
fi

DOCKER_OPTS="$DOCKER_OPTS -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) -e HOST_USERNAME=$(id -un)"

if [ -d "$HOME/.aws" ]; then
  DOCKER_OPTS="$DOCKER_OPTS --mount type=bind,source=$HOME/.aws,target=/home/user/.aws"
fi

if [ -d "$HOME/.ssh" ]; then
  DOCKER_OPTS="$DOCKER_OPTS --mount type=bind,source=$HOME/.ssh,target=/home/user/.ssh"
fi

if [ -d "$HOME/.c9" ]; then
  # We're in Cloud9
  DOCKER_OPTS="$DOCKER_OPTS -e IS_CLOUD9=true"
else
  # We're not in Cloud9
  DOCKER_OPTS="$DOCKER_OPTS -e AWS_PROFILE=$SITE_NAME"
fi

# DOCKER_OPTS="$DOCKER_OPTS -u 0:1000"

#
# This probably works on Linux but not on macos:
# https://github.com/docker/for-mac/issues/483
#
#if [ -n "$SSH_AUTH_SOCK" ]; then
#  SOCK_DIR="$(dirname $SSH_AUTH_SOCK)"
#  if [ -d "$SOCK_DIR" ]; then
#    DOCKER_OPTS="$DOCKER_OPTS -v $SOCK_DIR:$SOCK_DIR -e SSH_AUTH_SOCK=$SSH_AUTH_SOCK"
#  else
#    echo "WARNING: SSH_AUTH_SOCK is set to '$SSH_AUTH_SOCK' but '$SOCK_DIR' is not a directory."
#  fi
#fi

docker run -ti --rm --mount type=bind,source="$SCRIPT_DIR/..",target=/repo $DOCKER_OPTS $IMAGE /bin/bash /launch.sh
