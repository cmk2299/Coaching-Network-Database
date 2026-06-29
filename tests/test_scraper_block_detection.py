"""Unit tests for scrape_person_profiles.looks_like_block — the sentinel that
prevents the scraper from caching anti-bot / interstitial pages as valid
profiles for 30 days (the P0 data-corruption vector from AUDIT_2026-06-20).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))
from scrape_person_profiles import looks_like_block  # noqa: E402


# Helpers
PROFILE_HOOK = "/profil/spieler/"
FILL = "x" * 4000  # comfortably above MIN_PROFILE_LEN (3000)


class TestLooksLikeBlock:
    # Empty / short bodies
    def test_empty_string_is_block(self):
        assert looks_like_block("") is True

    def test_none_is_block(self):
        assert looks_like_block(None) is True

    def test_too_short_body_is_block(self):
        assert looks_like_block("<html>short</html>") is True

    def test_just_under_min_len_is_block(self):
        assert looks_like_block("x" * 2999) is True

    # Block markers (any case)
    def test_cloudflare_just_a_moment(self):
        body = "<html>" + FILL + " Just a moment... " + FILL + PROFILE_HOOK + "</html>"
        assert looks_like_block(body) is True

    def test_captcha_marker(self):
        body = "<html>" + FILL + " CAPTCHA verification " + PROFILE_HOOK + "</html>"
        assert looks_like_block(body) is True

    def test_german_zugriff_verweigert(self):
        body = "<html>" + FILL + " Zugriff verweigert " + PROFILE_HOOK + "</html>"
        assert looks_like_block(body) is True

    def test_rate_limit_marker(self):
        body = "<html>" + FILL + " Rate limit exceeded " + PROFILE_HOOK + "</html>"
        assert looks_like_block(body) is True

    def test_cf_challenge_path(self):
        body = "<html>" + FILL + ' src="/cdn-cgi/challenge-platform/foo" ' + PROFILE_HOOK + "</html>"
        assert looks_like_block(body) is True

    # Profile markers required
    def test_long_body_without_any_profile_marker_is_block(self):
        body = "<html>" + FILL + "some unrelated content here" + FILL + "</html>"
        assert looks_like_block(body) is True

    # Genuine profile bodies pass
    def test_real_profile_with_data_header(self):
        body = "<html>" + FILL + '<div class="data-header"> spieler </div>' + FILL + "</html>"
        assert looks_like_block(body) is False

    def test_real_profile_with_info_table(self):
        body = "<html>" + FILL + '<div class="info-table"> Name: X </div>' + FILL + "</html>"
        assert looks_like_block(body) is False

    def test_real_profile_with_profil_link(self):
        body = "<html>" + FILL + ' href="/x/profil/spieler/123" ' + FILL + "</html>"
        assert looks_like_block(body) is False

    # Defense: a block page that happens to contain a profile marker is still a block
    def test_block_marker_wins_over_profile_marker(self):
        body = "<html>" + FILL + " just a moment " + FILL + PROFILE_HOOK + "</html>"
        assert looks_like_block(body) is True
