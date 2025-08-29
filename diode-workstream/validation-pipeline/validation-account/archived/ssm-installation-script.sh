#!/bin/bash -xe

SERVICE_ROOT_WORKING_DIR="/tmp/imagebuilder_service"
WORKING_DIR="/tmp"
AWS_REGION="us-gov-west-1"
S3_ENDPOINT="https://s3.us-gov-west-1.amazonaws.com"
MAX_RETRY_ATTEMPTS=5
MAX_RETRY_SECONDS=120

function error_exit {
    echo "$1" 1>&2
    exit 1
}

function retry_command() {
    command=$1
    max_attempts=$2
    delay=$3
    attempts=0
    while [[ $attempts -lt $max_attempts ]]
    do
        $command && return
        exit_code=$?
        attempts=$((attempts+1))
        echo "$command exited with $exit_code, attempt $attempts/$max_attempts. Waiting $delay seconds."
        sleep $delay
    done
    error_exit "$command failed after $attempts attempts"
}

function validate_http_status_code(){
	url="$1"
	http_status="$2"
	echo "URL '$url' returned HTTP status '$http_status'"
	if [ $http_status != "200" ] ; then
		exit 1
	fi
}

function package_exists() {
    $(which "$1" > /dev/null 2>&1 )
    return $?
}

function is_ssm_agent_installed() {
    $(sudo rpm -q amazon-ssm-agent > /dev/null 2>&1)
    return $?
}

function get_arch() {
    if [ "$(uname -m)" == "x86_64" ]; then
        echo "amd64"
    elif [ "$(uname -m)" == "aarch64" ]; then
        echo "arm64"
    else
        error_exit "Unsupported architecture $(uname -m)"
    fi
}

function install_ssm_agent() {
    arch="$(get_arch)"
    if package_exists rpm ; then
        ssm_agent_url=${S3_ENDPOINT}/amazon-ssm-${AWS_REGION}/latest/linux_${arch}/amazon-ssm-agent.rpm
        http_status_code=$(sudo curl -w "%{http_code}" -o ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.rpm $ssm_agent_url --retry $MAX_RETRY_ATTEMPTS --retry-max-time $MAX_RETRY_SECONDS)
        validate_http_status_code $ssm_agent_url $http_status_code
        retry_command "sudo rpm --install ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.rpm" 5 30
        sudo rm -f ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.rpm
        sudo echo "rpm" > ${SERVICE_ROOT_WORKING_DIR}/ssm_installed
    elif package_exists yum ; then
        retry_command "sudo yum install -y ${S3_ENDPOINT}/amazon-ssm-${AWS_REGION}/latest/linux_${arch}/amazon-ssm-agent.rpm" 5 30
        sudo echo "yum" > ${SERVICE_ROOT_WORKING_DIR}/ssm_installed
    elif package_exists snap ; then
        sudo wget -O ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.snap ${S3_ENDPOINT}/amazon-ssm-${AWS_REGION}/latest/debian_${arch}/amazon-ssm-agent.snap
        sudo wget -O ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.assert ${S3_ENDPOINT}/amazon-ssm-${AWS_REGION}/latest/debian_${arch}/amazon-ssm-agent.assert
        sudo snap ack ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.assert
        sudo snap install --classic ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.snap
        sudo rm -f ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.snap
        sudo rm -f ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.assert
        sudo echo "snap" >  ${SERVICE_ROOT_WORKING_DIR}/ssm_installed
    elif package_exists dpkg ; then
        sudo wget --force-directories -O ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.deb ${S3_ENDPOINT}/amazon-ssm-${AWS_REGION}/latest/debian_${arch}/amazon-ssm-agent.deb
        sudo dpkg -i ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.deb
        sudo rm -f ${SERVICE_ROOT_WORKING_DIR}/amazon-ssm-agent.deb
        sudo echo "dpkg" > ${SERVICE_ROOT_WORKING_DIR}/ssm_installed
    elif package_exists pkg ; then
        su -m root -c "pkg install -y amazon-ssm-agent pidof"
        su -m root -c 'echo "pkg" > ${SERVICE_ROOT_WORKING_DIR}/ssm_installed'
    else
        error_exit "Unable to install an SSM agent"
    fi
}

function is_active() {
    pidof amazon-ssm-agent
    return $?
}

function start_ssm_agent() {
    if command -v start 1>/dev/null; then
        sudo start amazon-ssm-agent
    else
        echo "Not a known service"
    fi
}

function sys_init_bootstrap() {
    if is_ssm_agent_installed ; then
        echo "SSM Agent is already installed"
    else
        install_ssm_agent
    fi

    if is_active ; then
        echo "SSM Agent is already installed and running on this instance"
    else
        start_ssm_agent
    fi
}

function install_crontab() {
    os_type="$(get_os_type)"
    case ${os_type} in
      'amzn')
        echo "Installing cronie package"
        retry_command "sudo yum install -y cronie" 5 30
        sudo echo -n > ${SERVICE_ROOT_WORKING_DIR}/crontab_installed
        ;;
    esac
}

function get_os_type() {
    FILE=/etc/os-release
    if [ -e $FILE ]; then
        . $FILE
        echo $ID
    else
        echo ""
    fi
}

mkdir -p ${SERVICE_ROOT_WORKING_DIR}

if [ "$(cat /proc/1/comm)" == "systemd" ]; then
    if [[ "$(systemctl is-active amazon-ssm-agent)" == "active" || "$(systemctl is-active snap.amazon-ssm-agent.amazon-ssm-agent)" == "active" ]]; then
        echo "SSM Agent is already installed and running on this instance"
    else
        if is_ssm_agent_installed ; then
            echo "SSM Agent is installed but not running"
        else
            install_ssm_agent
        fi

        sudo systemctl daemon-reload
        if [ "$(cat ${SERVICE_ROOT_WORKING_DIR}/ssm_installed)" == "snap" ]; then
            sudo systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service
            sudo systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service
        else
            sudo systemctl enable amazon-ssm-agent
            sudo systemctl start amazon-ssm-agent
        fi
    fi
elif [  "$(cat /proc/1/comm)" == "init"  ]; then
    sys_init_bootstrap
elif [ -d "/etc/rc.d" ]; then
    if is_ssm_agent_installed ; then
        echo "SSM Agent is already installed"
    else
        install_ssm_agent
    fi

    if is_active ; then
        echo "SSM Agent is already running"
    else
        su -m root -c "/usr/local/etc/rc.d/amazon-ssm-agent onestart"
    fi
fi

if ! package_exists crontab ; then
  echo 'Crontab command not found, installing'
  install_crontab
fi
