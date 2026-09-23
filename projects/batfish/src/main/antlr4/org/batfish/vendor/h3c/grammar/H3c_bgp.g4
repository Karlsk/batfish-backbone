parser grammar H3c_bgp;

options { tokenVocab = H3cLexer; }

bgp_statement: BGP h3c_words;
