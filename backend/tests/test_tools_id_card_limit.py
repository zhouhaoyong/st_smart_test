import unittest

from api.v1.endpoints.tools import IdCardRequest, UnifiedException, generate_id_card


class IdCardGenerationLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_allows_up_to_one_hundred_records(self):
        result = await generate_id_card(IdCardRequest(count=100), current_user=None)

        self.assertEqual(len(result["data"]["records"]), 100)

    async def test_rejects_more_than_one_hundred_records(self):
        with self.assertRaisesRegex(UnifiedException, "生成数量应在1至100之间"):
            await generate_id_card(IdCardRequest(count=101), current_user=None)


if __name__ == "__main__":
    unittest.main()
