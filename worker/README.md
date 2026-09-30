# Worker sonda — infraestructura de semana 1

Este contenedor solo prueba conectividad SQL con PostgreSQL (`SELECT 1`) y mantiene un pulso de salud. Docker lo reinicia si el proceso termina. No contiene Gemini, LangGraph, Discord ni procesamiento asíncrono real.

La implementación del worker de procesamiento y sus estados corresponde a la actividad posterior. Reemplazar esta sonda durante esa integración, conservando la red privada, las variables de entorno y un healthcheck adecuado.
