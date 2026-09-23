parser grammar H3c_policy;

options { tokenVocab = H3cLexer; }

policy_statement: ROUTE_POLICY h3c_words;
