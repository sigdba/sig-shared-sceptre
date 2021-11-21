SSH_ENV="$HOME/.ssh-agent-env"

start_agent () {
    echo "Initialising new SSH agent..."
    /usr/bin/ssh-agent | sed 's/^echo/#echo/' > "${SSH_ENV}"
    chmod 600 "${SSH_ENV}"
    . "${SSH_ENV}" > /dev/null
}

# Source SSH settings, if applicable

if [ -f "${SSH_ENV}" ]; then
    . "${SSH_ENV}" > /dev/null
    ps -ef | grep ${SSH_AGENT_PID} | grep ssh-agent$ > /dev/null || {
        start_agent;
    }
else
    start_agent;
fi

. /repo/dev/site.conf

if [ -f /etc/is_cloud9 ]; then
    echo "Cloud9 detected"
else
    export AWS_PROFILE="sig"
fi

find $HOME/.ssh -type f -name "$SITE_NAME"'[-_]*.pem' -exec ssh-add '{}' ';'

export PS1="($SITE_NAME) \w \$ "

cd /repo
