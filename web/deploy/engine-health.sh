#!/bin/bash
set -eu
exec 3<>/dev/tcp/127.0.0.1/9996
printf 'GET /v2/version HTTP/1.0\r\nHost: localhost\r\n\r\n' >&3
read -r status <&3
[[ "$status" == *" 200 "* ]]
