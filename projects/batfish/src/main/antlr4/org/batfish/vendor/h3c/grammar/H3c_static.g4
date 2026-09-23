parser grammar H3c_static;

options { tokenVocab = H3cLexer; }

static_statement: (IP | IPV6) ROUTE_STATIC h3c_words;
