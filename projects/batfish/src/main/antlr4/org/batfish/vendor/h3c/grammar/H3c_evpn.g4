parser grammar H3c_evpn;

options { tokenVocab = H3cLexer; }

evpn_statement: (VSI | XCONNECT_GROUP | SEGMENT_ROUTING) h3c_words;
