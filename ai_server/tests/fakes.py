"""테스트 전용 가짜 Gemini 클라이언트 래퍼 (실제 google.genai.Client 대체).

test_gemini_client.py와 test_embed_client.py가 client.aio.models.*를 흉내
내는 구조가 동일해서(embed_content vs generate_content만 다름) 공통 부분을
여기로 뺀다. 각 테스트 파일은 자신의 FakeModels(메서드가 다름)만 만들어서
FakeClient(models=...)에 넣으면 된다.
"""


class FakeAio:
    def __init__(self, models):
        self.models = models


class FakeClient:
    def __init__(self, models):
        self.aio = FakeAio(models)
