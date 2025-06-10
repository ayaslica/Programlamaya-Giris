import React, { useEffect, useState } from 'react';
import { View, Text, Button, FlatList, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function DreamListScreen({ navigation }) {
  const [dreams, setDreams] = useState([]);
  const [username, setUsername] = useState('');

  useEffect(() => {
    const loadData = async () => {
      const name = await AsyncStorage.getItem('username');
      const saved = await AsyncStorage.getItem('dreams');
      setUsername(name || '');
      setDreams(saved ? JSON.parse(saved) : []);
    };
    const unsubscribe = navigation.addListener('focus', loadData);
    return unsubscribe;
  }, [navigation]);

  const renderItem = ({ item }) => (
    <View style={styles.item}>
      <Text style={styles.itemText}>{item.text}</Text>
      <Text style={styles.itemInterp}>{item.interpretation}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Hello {username}</Text>
      <Button
        title="Add Dream"
        onPress={() => navigation.navigate('NewDream')}
      />
      <FlatList
        data={dreams}
        renderItem={renderItem}
        keyExtractor={(item, index) => index.toString()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  title: { fontSize: 20, marginBottom: 12 },
  item: { marginBottom: 12, padding: 8, borderWidth: 1, borderColor: '#eee' },
  itemText: { marginBottom: 4 },
  itemInterp: { fontStyle: 'italic', color: '#555' },
});
