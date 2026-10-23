def test_prompt_exists():
    import pathlib
    assert (pathlib.Path(__file__).resolve().parents[1] / "prompts" / "answer.md").read_text().strip()
