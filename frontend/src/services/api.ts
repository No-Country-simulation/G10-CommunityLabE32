import axios from 'axios';

// Configuración base apuntando a tu FastAPI
export const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Tipado estricto basado en tu Pydantic del Backend
export interface Mensaje {
  id_mensaje: string;
  autor: string;
  fecha: string;
  canal: string;
  tipo: string;
  texto: string;
  sentimiento_ref?: string;
  tema_ref?: string;
}

export const obtenerMensajes = async (canal?: string): Promise<Mensaje[]> => {
  const response = await apiClient.get('/mensajes', { params: { canal } });
  return response.data;
};

export const subirLote = async (archivo: File) => {
  const formData = new FormData();
  formData.append('file', archivo);

  const response = await apiClient.post('/mensajes/procesamientos', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};