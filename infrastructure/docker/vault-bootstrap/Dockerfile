FROM alpine:3.20

RUN apk add --no-cache curl jq ca-certificates

COPY bootstrap.sh /bootstrap.sh
RUN chmod +x /bootstrap.sh

ENTRYPOINT ["/bootstrap.sh"]
