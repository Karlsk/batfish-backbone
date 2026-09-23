parser grammar H3c_vpn;

options { tokenVocab = H3cLexer; }

vpn_statement: IP VPN_INSTANCE h3c_words;
