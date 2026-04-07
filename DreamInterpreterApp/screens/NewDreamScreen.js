import React, { useState } from 'react';
import { View, TextInput, Button, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getDreamInterpretation } from '../utils/openai';

export default function NewDreamScreen({ navigation }) {
  const [dreamText, setDreamText] = useState('');

  const handleSave = async () => {
    if (dreamText.trim().length === 0) return;
    const saved = await AsyncStorage.getItem('dreams');
    const dreams = saved ? JSON.parse(saved) : [];
    const interpretation = await getDreamInterpretation(dreamText, dreams);
    const newDream = { text: dreamText, interpretation };
    const updatedDreams = [newDream, ...dreams];
    await AsyncStorage.setItem('dreams', JSON.stringify(updatedDreams));
    navigation.goBack();
  };

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        placeholder="Describe your dream"
        value={dreamText}
        onChangeText={setDreamText}
        multiline
      />
      <Button title="Save Dream" onPress={handleSave} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 8,
    marginBottom: 12,
    height: 120,
    textAlignVertical: 'top',
  },
});
