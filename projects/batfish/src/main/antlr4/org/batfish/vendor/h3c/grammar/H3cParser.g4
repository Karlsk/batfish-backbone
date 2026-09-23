parser grammar H3cParser;

import H3c_common, H3c_interface, H3c_vpn, H3c_static, H3c_isis, H3c_bgp, H3c_policy, H3c_evpn;

options { tokenVocab = H3cLexer; superClass = 'org.batfish.grammar.BatfishParser'; }

// The statement tree resolves Comware views. Feature extractors validate every
// statement in target views; an unknown WORD sequence is never silently accepted.
h3c_configuration: (statement | NEWLINE)* EOF;
statement: INDENT? (interface_statement | vpn_statement | static_statement
    | isis_statement | bgp_statement | policy_statement | evpn_statement
    | other_statement) NEWLINE;
other_statement: h3c_word+;
