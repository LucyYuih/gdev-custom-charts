
import webview
import sys
import os
import threading

def run_game():
    # Lógica para encontrar o caminho correto quando empacotado
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    html_path = os.path.join(base_dir, 'assets', 'index.html')
    
    # Verifica se o arquivo existe
    if not os.path.exists(html_path):
        webview.create_window('Erro', html=f'<h1>Erro: Arquivo não encontrado</h1><p>{html_path}</p>')
    else:
        webview.create_window('fnf online', url=html_path, width=1920, height=1080, resizable=True)

    webview.start()

if __name__ == '__main__':
    run_game()
