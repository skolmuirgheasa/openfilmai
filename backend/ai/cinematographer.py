"""
AI Cinematographer - Generates shot lists from scene descriptions using LLM.
Takes scene context, dialogue, and character info to create detailed shot plans
with camera angles, subjects, actions, and prompt suggestions.
"""
import json
import logging
from typing import Optional, List, Dict, Any
import requests

logger = logging.getLogger(__name__)

SHOT_PLANNING_SYSTEM_PROMPT = '''You are an expert cinematographer and film director with deep knowledge of visual storytelling.

Given a scene description and/or dialogue, create a detailed shot list that provides complete editorial coverage.

## Shot Types to Consider:
- **Establishing/Wide**: Set the scene, show location and spatial relationships
- **Medium**: Standard conversational framing, waist-up
- **Close-up**: Emotional moments, reactions, important dialogue
- **Extreme Close-up**: Insert shots, details, intense emotion
- **Over-the-shoulder (OTS)**: Dialogue scenes, creates connection
- **Two-shot**: Two characters in frame together
- **POV**: Subjective view from character's perspective
- **Reaction shots**: Character responses to events

## Guidelines:
1. Start with an establishing shot to orient viewers
2. Vary shot sizes for visual interest (don't do 5 close-ups in a row)
3. Cover important dialogue with close-ups
4. Include reaction shots for emotional beats
5. Use OTS shots to establish eyelines in conversations
6. End scenes with shots that provide closure or transition

## For Each Shot, Provide:
- shot_number: Sequential number
- camera_angle: One of "Extreme Wide", "Wide", "Medium Wide", "Medium", "Medium Close-up", "Close-up", "Extreme Close-up", "Over-the-shoulder", "POV", "Two-shot", "Insert"
- subject: Who or what is the focus (character name or description)
- characters_visible: Array of character names who appear in this shot (use exact names from the character list)
- action: What happens in this shot (brief description)
- dialogue: Any lines spoken in this shot (exact text if provided, null otherwise)
- speaker: Name of character speaking (if dialogue present, null otherwise)
- duration_suggestion: Suggested duration in seconds (2-8 typically)
- prompt_suggestion: A detailed image generation prompt for the start frame

## IMPORTANT - Character Identification:
- For EVERY shot, identify ALL characters who would be visible in frame
- Use the EXACT character names provided in the character list
- For OTS shots, include both characters (one in foreground, one in background)
- For Two-shots, include both characters
- For reaction shots, include the character reacting

## Prompt Writing Tips:
- Be specific about lighting, mood, and atmosphere
- Include camera/lens details: "35mm film", "shallow depth of field", "anamorphic"
- Reference the character by name if known
- Include relevant scene context (location, time of day)
- Add style keywords: "cinematic", "film grain", "professional color grading"
- If visual style notes are provided, incorporate them into every prompt

Return ONLY a valid JSON array. No markdown, no explanation, just the JSON array.'''

EXAMPLE_OUTPUT = '''[
  {
    "shot_number": 1,
    "camera_angle": "Wide",
    "subject": "Warehouse exterior",
    "action": "Establishing shot of the abandoned warehouse at dusk",
    "dialogue": null,
    "duration_suggestion": 4,
    "prompt_suggestion": "Cinematic wide shot of an abandoned industrial warehouse at golden hour, dramatic shadows, rusted metal walls, broken windows, atmospheric fog, 35mm film, anamorphic lens flare"
  },
  {
    "shot_number": 2,
    "camera_angle": "Medium",
    "subject": "Jonas",
    "action": "Jonas enters through the main door, looking around cautiously",
    "dialogue": null,
    "duration_suggestion": 5,
    "prompt_suggestion": "Medium shot of a man entering a dark warehouse doorway, backlit by golden sunset light, dust particles in air, cautious expression, cinematic lighting, film grain"
  }
]'''


def generate_shot_list(
    scene_description: str,
    dialogue: Optional[str] = None,
    characters: Optional[List[Dict[str, Any]]] = None,
    location_notes: Optional[str] = None,
    visual_style: Optional[str] = None,
    color_palette: Optional[str] = None,
    camera_style: Optional[str] = None,
    tone_notes: Optional[str] = None,
    num_shots: Optional[int] = None,
    provider: str = "anthropic",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate a shot list from scene description using LLM.

    Args:
        scene_description: Main description of what happens in the scene
        dialogue: Script dialogue for the scene (if any)
        characters: List of character dicts with name, style_tokens, etc.
        location_notes: Additional notes about the setting
        visual_style: Overall visual style (e.g., "gritty noir")
        color_palette: Color preferences (e.g., "desaturated blues")
        camera_style: Camera approach (e.g., "handheld documentary")
        tone_notes: Additional cinematography notes
        num_shots: Approximate number of shots to generate (optional hint)
        provider: "anthropic" or "openai"
        api_key: API key for the provider

    Returns:
        List of shot dictionaries with planning fields
    """
    if not api_key:
        raise ValueError(f"No API key provided for {provider}")

    # Build context message
    context_parts = []

    if scene_description:
        context_parts.append(f"## Scene Description\n{scene_description}")

    if dialogue:
        context_parts.append(f"## Dialogue\n{dialogue}")

    if characters:
        char_info = []
        for c in characters:
            char_str = f"- **{c.get('name', 'Unknown')}**"
            if c.get('style_tokens'):
                char_str += f": {c.get('style_tokens')}"
            if c.get('appearance_notes'):
                char_str += f" (Scene appearance: {c.get('appearance_notes')})"
            char_info.append(char_str)
        if char_info:
            context_parts.append(f"## Characters in Scene\nThese are the characters available. Use their names EXACTLY as shown in characters_visible:\n" + "\n".join(char_info))

    if location_notes:
        context_parts.append(f"## Location Notes\n{location_notes}")

    # Visual style section - IMPORTANT for prompt generation
    style_parts = []
    if visual_style:
        style_parts.append(f"Visual Style: {visual_style}")
    if color_palette:
        style_parts.append(f"Color Palette: {color_palette}")
    if camera_style:
        style_parts.append(f"Camera Style: {camera_style}")
    if tone_notes:
        style_parts.append(f"Tone: {tone_notes}")
    if style_parts:
        context_parts.append(f"## Visual Style Guidelines\nIncorporate these into EVERY prompt_suggestion:\n" + "\n".join(style_parts))

    if num_shots:
        context_parts.append(f"## Target Shot Count\nAim for approximately {num_shots} shots.")

    user_message = "\n\n".join(context_parts)
    user_message += "\n\nCreate a comprehensive shot list for this scene. Return ONLY a JSON array."

    logger.info(f"Generating shot list with {provider}, context length: {len(user_message)}")

    if provider == "anthropic":
        return _call_anthropic(user_message, api_key)
    elif provider == "openai":
        return _call_openai(user_message, api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_anthropic(user_message: str, api_key: str) -> List[Dict[str, Any]]:
    """Call Claude API for shot planning."""
    logger.info("Calling Anthropic API (claude-sonnet-4-20250514)...")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",  # Latest Claude Sonnet 4
            "max_tokens": 8192,
            "system": SHOT_PLANNING_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}]
        },
        timeout=120
    )

    if response.status_code != 200:
        error_detail = response.text
        logger.error(f"Anthropic API error: {response.status_code} - {error_detail}")
        raise RuntimeError(f"Anthropic API error: {response.status_code} - {error_detail}")

    data = response.json()
    content = data.get("content", [{}])[0].get("text", "")
    logger.info(f"Anthropic response length: {len(content)}")

    return _parse_shot_list(content)


def _call_openai(user_message: str, api_key: str) -> List[Dict[str, Any]]:
    """Call OpenAI API for shot planning."""
    logger.info("Calling OpenAI API (gpt-4.1-2025-04-14)...")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4.1-2025-04-14",  # Latest GPT-4.1 (April 2025)
            "messages": [
                {"role": "system", "content": SHOT_PLANNING_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 8192
        },
        timeout=120
    )

    if response.status_code != 200:
        error_detail = response.text
        logger.error(f"OpenAI API error: {response.status_code} - {error_detail}")
        raise RuntimeError(f"OpenAI API error: {response.status_code} - {error_detail}")

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    logger.info(f"OpenAI response length: {len(content)}")

    return _parse_shot_list(content)


def _parse_shot_list(content: str) -> List[Dict[str, Any]]:
    """Parse LLM response into shot list, handling various response formats."""
    content = content.strip()

    # Remove markdown code blocks if present
    if "```" in content:
        # Find content between first ``` and last ```
        lines = content.split("\n")
        in_block = False
        block_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    break  # End of block
                else:
                    in_block = True
                    continue  # Skip the opening ```json line
            if in_block:
                block_lines.append(line)
        if block_lines:
            content = "\n".join(block_lines)

    # Find JSON array boundaries
    start_idx = content.find("[")
    end_idx = content.rfind("]")

    if start_idx != -1 and end_idx > start_idx:
        json_str = content[start_idx:end_idx + 1]
        try:
            shots = json.loads(json_str)
            if isinstance(shots, list):
                logger.info(f"Parsed {len(shots)} shots from response")
                return shots
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Content snippet: {json_str[:500]}...")

    # Try parsing entire content as JSON
    try:
        shots = json.loads(content)
        if isinstance(shots, list):
            return shots
    except json.JSONDecodeError:
        pass

    raise ValueError("Could not parse shot list from LLM response")


def refine_shot_prompt(
    shot: Dict[str, Any],
    scene_context: str,
    character_info: Optional[str] = None,
    style_notes: Optional[str] = None,
    provider: str = "anthropic",
    api_key: Optional[str] = None
) -> str:
    """
    Refine a single shot's prompt with more detail.

    Args:
        shot: The shot dict with existing prompt_suggestion
        scene_context: Overall scene description
        character_info: Character appearance details
        style_notes: Visual style preferences
        provider: LLM provider
        api_key: API key

    Returns:
        Refined prompt string
    """
    if not api_key:
        return shot.get("prompt_suggestion", "")

    system = """You are an expert at writing prompts for AI image generation.
Given a shot description and context, write a detailed, evocative prompt that will generate
a high-quality cinematic still frame.

Focus on:
- Specific visual details
- Lighting and atmosphere
- Camera/lens characteristics
- Character appearance (if applicable)
- Mood and emotion

Return ONLY the prompt text, nothing else."""

    user = f"""Shot: {shot.get('camera_angle', 'Medium')} of {shot.get('subject', 'scene')}
Action: {shot.get('action', '')}
Scene Context: {scene_context}
"""
    if character_info:
        user += f"Character Details: {character_info}\n"
    if style_notes:
        user += f"Style: {style_notes}\n"
    user += f"\nCurrent prompt suggestion: {shot.get('prompt_suggestion', '')}\n\nWrite an improved, more detailed prompt:"

    try:
        if provider == "anthropic":
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "system": system,
                    "messages": [{"role": "user", "content": user}]
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("content", [{}])[0].get("text", "").strip()
        else:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    "max_tokens": 500
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"Error refining prompt: {e}")

    return shot.get("prompt_suggestion", "")
