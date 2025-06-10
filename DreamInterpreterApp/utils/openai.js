import Constants from 'expo-constants';

const apiKey = Constants?.manifest?.extra?.openaiApiKey || 'YOUR_API_KEY';
const endpoint = 'https://api.openai.com/v1/chat/completions';

export async function getDreamInterpretation(dream, pastDreams) {
  try {
    const messages = [
      { role: 'system', content: 'You are a helpful dream interpreter.' },
      { role: 'user', content: `Previous dreams: ${pastDreams.map(d => d.text).join('\n')}` },
      { role: 'user', content: `New dream: ${dream}` },
    ];

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-3.5-turbo',
        messages,
      }),
    });
    const data = await response.json();
    const interpretation = data.choices?.[0]?.message?.content || '';
    return interpretation.trim();
  } catch (err) {
    console.error('GPT request failed', err);
    return 'Interpretation unavailable';
  }
}
