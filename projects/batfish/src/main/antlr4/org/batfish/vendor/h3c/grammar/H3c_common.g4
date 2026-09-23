parser grammar H3c_common;

options { tokenVocab = H3cLexer; }

h3c_word: ~(INDENT | NEWLINE);
h3c_words: h3c_word*;
