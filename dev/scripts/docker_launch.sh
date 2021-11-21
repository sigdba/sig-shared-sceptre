#!/bin/bash

#
# This is the entry script for the docker-dev container. It runs as root
# and sets up the container user to match the host user's UID & GID.
#

die () {
	echo "ERROR: $*"
	exit 1
}

[ -z "$HOST_UID" ] && die "HOST_UID not set"
[ -z "$HOST_GID" ] && die "HOST_GID not set"
[ -z "$HOST_USERNAME" ] && die "HOST_USERNAME not set"

USER_HOME="/home/user"

if [ "$IS_CLOUD9" == 'true' ]; then
  # export TERM=vt220
  touch /etc/is_cloud9
else
	rm -f /etc/is_cloud9
fi

groupadd -g $HOST_GID user
useradd -u $HOST_UID -g $HOST_GID -M -N -d $USER_HOME -s /bin/zsh "$HOST_USERNAME"
cp -R /root/.oh-my-zsh $USER_HOME
chown -R $HOST_UID:$HOST_GID $USER_HOME
ln -s /home/user /home/$HOST_USERNAME

# su user -c /bin/bash
# su -l -c /bin/bash user
su - "$HOST_USERNAME"
