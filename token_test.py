from livekit.api import AccessToken, VideoGrants

api_key = "devkey"
api_secret = "secret"

token = (
    AccessToken(api_key, api_secret)
    .with_identity("test-user")
    .with_name("Test User")
    .with_grants(VideoGrants(room_join=True, room="testroom"))
    .to_jwt()
)

print(token)