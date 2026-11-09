"""
Gunicorn carga este fichero automaticamente si esta en la raiz del proyecto.
Subimos el timeout por defecto (30s) porque una edicion real (escritura del
Excel + subida a SharePoint via Graph) puede tardar mas que eso; con el
arreglo de asyncio.to_thread en los endpoints esto ya no deberia hacer falta
para evitar que Gunicorn mate el proceso, pero lo dejamos como red de
seguridad adicional.
"""
timeout = 300
