import unittest

from como_voto_generator.normalization import extract_section_label, normalize_vote


class NormalizationTests(unittest.TestCase):
    def test_normalize_vote_standard_values(self) -> None:
        self.assertEqual(normalize_vote("afirmativo"), "AFIRMATIVO")
        self.assertEqual(normalize_vote("NEGATIVO"), "NEGATIVO")
        self.assertEqual(normalize_vote("abstención"), "ABSTENCION")
        self.assertEqual(normalize_vote("Ausente"), "AUSENTE")
        self.assertEqual(normalize_vote("Presidente"), "PRESIDENTE")

    def test_normalize_vote_unknown_passthrough(self) -> None:
        self.assertEqual(normalize_vote("Licencia"), "LICENCIA")

    def test_extract_section_label_detects_general(self) -> None:
        self.assertEqual(
            extract_section_label("Votación EN GENERAL - O.D. 123/2024"),
            "En General",
        )

    def test_extract_section_label_detects_article(self) -> None:
        self.assertEqual(
            extract_section_label("Proyecto X - Artículo 5 - O.D. 123/2024"),
            "Art. 5",
        )


if __name__ == "__main__":
    unittest.main()
