import unittest

from como_voto_generator.normalization import normalize_name
from como_voto_generator.processing import build_legislator_data


class ProcessingTests(unittest.TestCase):
    def test_jxc_majority_includes_cambiemos_keyword(self) -> None:
        all_votaciones = [
            {
                "id": "v1",
                "chamber": "diputados",
                "title": "Ley de prueba",
                "date": "15/06/2020 - 12:00",
                "type": "EN GENERAL",
                "url": "https://example.test/votacion/v1",
                "votes": [
                    {
                        "name": "Diputado PJ",
                        "bloc": "Frente de Todos",
                        "province": "Buenos Aires",
                        "vote": "AFIRMATIVO",
                        "coalition": "PJ",
                    },
                    {
                        "name": "Diputado Cambiemos",
                        "bloc": "Cambiemos",
                        "province": "CABA",
                        "vote": "NEGATIVO",
                        "coalition": "OTROS",
                    },
                ],
            }
        ]
        law_groups = {
            "g1": {
                "title": "Ley de prueba",
                "common_name": "Ley de prueba",
                "votaciones": [{"id": "v1", "chamber": "diputados"}],
            }
        }

        legislators = build_legislator_data(all_votaciones, law_groups)
        pj_key = normalize_name("Diputado PJ")

        self.assertIn(pj_key, legislators)
        self.assertEqual(legislators[pj_key]["votes"][0]["pro"], "NEGATIVO")
        self.assertEqual(legislators[pj_key]["alignment"]["PRO"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
