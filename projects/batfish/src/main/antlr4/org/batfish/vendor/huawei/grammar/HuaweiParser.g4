parser grammar HuaweiParser;
options { tokenVocab = HuaweiLexer; superClass = 'org.batfish.grammar.BatfishParser'; }
// The indentation tree supplies view context. Every command is subsequently
// validated by a view-specific extractor; unknown commands are parse warnings.
huawei_configuration: (statement | NEWLINE)* EOF;
statement: INDENT? command NEWLINE;
command: interface_command | routing_command | service_command | other_command;
interface_command: INTERFACE word+;
routing_command: (IP | IPV6 | ISIS | BGP | ROUTE_POLICY) word+;
service_command: (EVPN | EVPL | BRIDGE_DOMAIN | SEGMENT_ROUTING) word*;
other_command: WORD word*;
word: WORD | INTERFACE | IP | IPV6 | ISIS | BGP | ROUTE_POLICY | EVPN | EVPL | BRIDGE_DOMAIN | SEGMENT_ROUTING;
