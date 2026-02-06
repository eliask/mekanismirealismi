# Makefile for mekanismirealismi.fi static site

.PHONY: search-index

search-index:
	uv run --with beautifulsoup4 python build_search_index.py
