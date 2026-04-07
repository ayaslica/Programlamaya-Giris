# Dream Interpreter App

This is a simplified React Native application that runs on iOS and Android. It allows registered users to log their dreams and get personalized interpretations from GPT based on their dream history.

## Project Structure
- `App.js` - Entry point that sets up navigation.
- `screens/` - React components for various screens.
- `utils/openai.js` - Wrapper for GPT API calls.

## Running the app
1. Install dependencies (requires Node.js and npm):
   ```bash
   npm install
   ```
2. Start the Expo development server:
   ```bash
   npx expo start
   ```
3. Follow the on-screen instructions to run on iOS or Android.

This project uses Expo and React Navigation. You'll need an OpenAI API key in `utils/openai.js` to enable dream interpretation.
