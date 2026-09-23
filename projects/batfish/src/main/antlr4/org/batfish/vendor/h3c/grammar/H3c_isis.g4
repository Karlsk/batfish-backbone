parser grammar H3c_isis;

options { tokenVocab = H3cLexer; }

isis_statement: ISIS h3c_words;
