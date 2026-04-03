from llm import  llm_query_stream, llm_query, _calculate_tokens_usage_workaround

messages = [
    {
        'role': 'system',
        'content': """"Create the SPEC.md file for the 3D bonfire demo project.

Project: Bonfire in Forest - 3D Demo
Stack: HTML + JavaScript + Three.js (CDN)
Requirements:
1. Animated bonfire with procedural flame particles
2. Procedurally generated cabin model near the bonfire
3. Procedurally generated forest (trees, ground, grass)
4. Realistic appearance without image textures
5. Must work by opening index.html directly in browser (no server, no build)"""
    },
    {
        'role': 'user',
        'content': """## Files
### Created:
- SPEC.md

The specification includes:
- Visual design with complete color palette for night atmosphere
- Component specifications for bonfire (logs, flames, embers, stones), cabin (walls, roof, door, window, chimney), and forest (procedural trees, ground, grass)..."""
    }
]

result = llm_query(messages)#, max_tokens=1)
print("EXACTLY TOKENS:")
print(result['_usage'], "\n\n")

_stream = llm_query_stream(messages)

for chunk in list(_stream):
    if chunk['type'] == 'final':
        print(chunk)