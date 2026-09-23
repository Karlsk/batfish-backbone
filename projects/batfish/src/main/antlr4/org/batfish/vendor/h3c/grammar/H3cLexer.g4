lexer grammar H3cLexer;

options { superClass = 'H3cBaseLexer'; }

// View indentation must survive tokenization; interior spaces must not.
INDENT: {getCharPositionInLine() == 0}? [ \t]+;
INTERFACE: 'interface';
IP: 'ip';
IPV6: 'ipv6';
VPN_INSTANCE: 'vpn-instance';
ROUTE_STATIC: 'route-static';
ISIS: 'isis';
BGP: 'bgp';
ROUTE_POLICY: 'route-policy';
VSI: 'vsi';
XCONNECT_GROUP: 'xconnect-group';
SEGMENT_ROUTING: 'segment-routing';
WORD: ~[ \t\r\n]+;
NEWLINE: '\n';
WS: [ \t]+ -> channel(HIDDEN);
