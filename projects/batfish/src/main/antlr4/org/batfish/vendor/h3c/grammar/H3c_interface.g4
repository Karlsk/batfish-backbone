parser grammar H3c_interface;

options { tokenVocab = H3cLexer; }

interface_statement: INTERFACE h3c_words;
