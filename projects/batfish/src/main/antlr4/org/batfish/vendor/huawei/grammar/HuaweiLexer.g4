lexer grammar HuaweiLexer;
options { superClass = 'HuaweiBaseLexer'; }
INDENT: {getCharPositionInLine() == 0}? [ \t]+;
INTERFACE: 'interface';
IP: 'ip';
IPV6: 'ipv6';
ISIS: 'isis';
BGP: 'bgp';
ROUTE_POLICY: 'route-policy';
EVPN: 'evpn';
EVPL: 'evpl';
BRIDGE_DOMAIN: 'bridge-domain';
SEGMENT_ROUTING: 'segment-routing';
WORD: ~[ \t\r\n]+;
NEWLINE: '\n';
WS: [ \t]+ -> channel(HIDDEN);
