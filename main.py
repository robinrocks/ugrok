import logging
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
import requests
import json

logger = logging.getLogger(__name__)
EXTENSION_ICON = 'images/icon.png'

def wrap_text(text, max_w):
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        if len(current_line + word) <= max_w:
            current_line += ' ' + word
        else:
            lines.append(current_line.strip())
            current_line = word
    lines.append(current_line.strip())
    return '\n'.join(lines)

class GrokExtension(Extension):
    """
    Ulauncher extension to generate text using xAI's Grok API
    """

    def __init__(self):
        super(GrokExtension, self).__init__()
        logger.info('Grok extension started')
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

class KeywordQueryEventListener(EventListener):
    """
    Event listener for KeywordQueryEvent
    """

    def on_event(self, event, extension):
        endpoint = "https://api.x.ai/v1/chat/completions"

        logger.info('Processing user preferences')
        # Get user preferences
        try:
            api_key = extension.preferences['api_key']
            max_tokens = int(extension.preferences.get('max_tokens', 100))
            frequency_penalty = float(extension.preferences.get('frequency_penalty', 0.0))
            presence_penalty = float(extension.preferences.get('presence_penalty', 0.0))
            temperature = float(extension.preferences.get('temperature', 0.7))
            top_p = float(extension.preferences.get('top_p', 1.0))
            system_prompt = extension.preferences.get('system_prompt', 'You are Grok, created by xAI.')
            line_wrap = int(extension.preferences.get('line_wrap', 80))
            model = extension.preferences.get('model', 'grok-3-beta')  # Default to grok-beta
        except Exception as err:
            logger.error('Failed to parse preferences: %s', str(err))
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                   name='Failed to parse preferences: ' + str(err),
                                   on_enter=CopyToClipboardAction(str(err)))
            ])

        # Get search term
        search_term = event.get_argument()
        logger.info('The search term is: %s', search_term)
        # Display blank prompt if user hasn't typed anything
        if not search_term:
            logger.info('Displaying blank prompt')
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                   name='Type in a prompt...',
                                   on_enter=DoNothingAction())
            ])

        # Create POST request
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": search_term
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
        body = json.dumps(body)

        logger.info('Request body: %s', str(body))
        logger.info('Request headers: %s', str(headers))

        # Send POST request
        try:
            logger.info('Sending request')
            response = requests.post(
                endpoint, headers=headers, data=body, timeout=15)
            response.raise_for_status()  # Raise an exception for HTTP errors
        except requests.exceptions.RequestException as err:
            logger.error('Request failed: %s', str(err))
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                   name='Request failed: ' + str(err),
                                   on_enter=CopyToClipboardAction(str(err)))
            ])

        logger.info('Request succeeded')
        logger.info('Response: %s', str(response.text))

        # Parse response
        try:
            response_data = response.json()
            choices = response_data.get('choices', [])
            if not choices:
                logger.error('No choices in response: %s', str(response_data))
                return RenderResultListAction([
                    ExtensionResultItem(icon=EXTENSION_ICON,
                                       name='No response from Grok',
                                       on_enter=DoNothingAction())
                ])
        except Exception as err:
            logger.error('Failed to parse response: %s', str(response.text))
            err_msg = "Unknown error, please check logs for more info"
            try:
                err_msg = response_data.get('error', {}).get('message', err_msg)
            except Exception:
                pass
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                   name='Failed to parse response: ' + err_msg,
                                   on_enter=CopyToClipboardAction(err_msg))
            ])

        items = []
        try:
            for choice in choices:
                message = choice.get('message', {}).get('content', '')
                if not message:
                    continue
                message = wrap_text(message, line_wrap)
                items.append(ExtensionResultItem(
                    icon=EXTENSION_ICON,
                    name="Grok Response",
                    description=message,
                    on_enter=CopyToClipboardAction(message)
                ))
        except Exception as err:
            logger.error('Failed to process choices: %s', str(err))
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                   name='Failed to process response: ' + str(err),
                                   on_enter=CopyToClipboardAction(str(err)))
            ])

        if not items:
            logger.info('No valid responses to display')
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                   name='No valid response from Grok',
                                   on_enter=DoNothingAction())
            ])

        try:
            item_string = ' | '.join([item.description for item in items])
            logger.info("Results: %s", item_string)
        except Exception as err:
            logger.error('Failed to log results: %s', str(err))
            logger.error('Results: %s', str(items))

        return RenderResultListAction(items)

if __name__ == '__main__':
    GrokExtension().run()
