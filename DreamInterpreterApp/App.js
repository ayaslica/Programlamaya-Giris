import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import SignInScreen from './screens/SignInScreen';
import DreamListScreen from './screens/DreamListScreen';
import NewDreamScreen from './screens/NewDreamScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="SignIn">
        <Stack.Screen name="SignIn" component={SignInScreen} options={{ title: 'Sign In' }} />
        <Stack.Screen name="DreamList" component={DreamListScreen} options={{ title: 'My Dreams' }} />
        <Stack.Screen name="NewDream" component={NewDreamScreen} options={{ title: 'Add Dream' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
