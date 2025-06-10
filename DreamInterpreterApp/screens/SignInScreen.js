import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function SignInScreen({ navigation }) {
  const [username, setUsername] = useState('');

  const handleSignIn = async () => {
    if (username.trim().length === 0) return;
    await AsyncStorage.setItem('username', username);
    navigation.replace('DreamList');
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome</Text>
      <TextInput
        style={styles.input}
        placeholder="Enter your name"
        value={username}
        onChangeText={setUsername}
      />
      <Button title="Sign In" onPress={handleSignIn} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 16,
  },
  title: {
    fontSize: 24,
    marginBottom: 12,
    textAlign: 'center',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 8,
    marginBottom: 12,
  },
});
