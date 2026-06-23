"""
=============================================================
  CRUD DE PRODUTOS SISTEMA DE SUPRIMENTOS (ALMOXARIFADO/COMPRAS)
  Banco de Dados 2
=============================================================
  Integração com:
    sp_inserir_produto (procedure de INSERT)
    tg_antes_deletar_produto (trigger no DELETE)
    vw_dados_produtos (view de listagem)
    idx_produto_descricao (índice em descricao)
=============================================================
"""

import psycopg2
import psycopg2.extras
import os

# CONFIGURAÇÃO DA CONEXÃO
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "nomeDB"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "senha"),
}


# UTILITÁRIOS

def conectar():
    """Retorna uma conexão com o banco PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)


def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def pausar():
    input("\n  Pressione Enter para continuar...")


def linha(char="─", largura=60):
    print(char * largura)


def cabecalho(titulo: str):
    limpar_tela()
    linha("═")
    print(f"  {titulo}")
    linha("═")
    print()


def formatar_status(status: str) -> str:
    """Deixa o status visualmente destacado."""
    icones = {"OK": "OK", "COMPRAR": "COMPRAR"}
    return icones.get(status, status)


# 1. LISTAR PRODUTOS (usa a VIEW vw_dados_produtos)

def listar_produtos(busca: str = ""):
    """
    Consulta a view vw_dados_produtos.
    O parâmetro 'busca' filtra por descrição,
    aproveitando o índice idx_produto_descricao.
    """
    cabecalho("PRODUTOS CADASTRADOS")

    sql = """
        SELECT
            id_produto,
            descricao,
            unidade,
            estoque_minimo,
            estoque_atual,
            status_estoque
        FROM vw_dados_produtos
        WHERE descricao ILIKE %s
        ORDER BY descricao
    """

    conn = conectar()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, (f"%{busca}%",))
            produtos = cur.fetchall()

        if not produtos:
            print("  Nenhum produto encontrado.")
        else:
            print(f"  {'ID':<5} {'DESCRIÇÃO':<30} {'UN':<6} {'EST.MÍN':>8} "
                  f"{'ATUAL':>8}  STATUS")
            linha()
            for p in produtos:
                print(
                    f"  {p['id_produto']:<5} "
                    f"{p['descricao']:<30} "
                    f"{p['unidade']:<6} "
                    f"{float(p['estoque_minimo']):>8.2f} "
                    f"{float(p['estoque_atual']):>8.2f}  "
                    f"{formatar_status(p['status_estoque'])}"
                )
            linha()
            print(f"  Total: {len(produtos)} produto(s)")
    finally:
        conn.close()


# 2. BUSCAR PRODUTO POR ID (usa a VIEW)

def buscar_por_id(id_produto: int) -> dict | None:
    """Retorna os dados do produto pela view, ou None se não existir."""
    sql = """
        SELECT id_produto, descricao, unidade, estoque_minimo,
               estoque_atual, status_estoque
        FROM vw_dados_produtos
        WHERE id_produto = %s
    """
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, (id_produto,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def exibir_produto(p: dict):
    """Exibe os detalhes de um único produto."""
    print(f"  ID           : {p['id_produto']}")
    print(f"  Descrição    : {p['descricao']}")
    print(f"  Unidade      : {p['unidade']}")
    print(f"  Estoque Mín. : {float(p['estoque_minimo']):.2f}")
    print(f"  Estoque Atual: {float(p['estoque_atual']):.2f}")
    print(f"  Status       : {formatar_status(p['status_estoque'])}")


# 3. INSERIR PRODUTO (usa a PROCEDURE sp_inserir_produto)

def inserir_produto():
    cabecalho("CADASTRAR NOVO PRODUTO")

    print("  Preencha os dados do produto (deixe em branco para cancelar):\n")

    descricao = input("  Descrição  : ").strip()
    if not descricao:
        print("\n  Operação cancelada.")
        pausar()
        return

    unidade = input("  Unidade (ex: UN, CX, PCT, GL, FR): ").strip().upper()
    if not unidade:
        print("\n  Operação cancelada.")
        pausar()
        return

    try:
        est_min = float(input("  Estoque mínimo: ").strip())
    except ValueError:
        print("\nValor inválido para estoque mínimo.")
        pausar()
        return

    print()
    confirm = input(f"  Confirmar cadastro de '{descricao}'? (s/n): ").strip().lower()
    if confirm != "s":
        print("  Operação cancelada.")
        pausar()
        return

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CALL sp_inserir_produto(%s, %s, %s, NULL);",
                (descricao, unidade, est_min)
            )
            cur.execute(
                "SELECT id_produto FROM produto WHERE descricao = %s "
                "ORDER BY id_produto DESC LIMIT 1",
                (descricao,)
            )
            row = cur.fetchone()
            novo_id = row[0] if row else "?"
        conn.commit()
        print(f"\nProduto cadastrado com sucesso! ID: {novo_id}")
        print(f"     Um registro de estoque zerado foi criado automaticamente.")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"\nErro ao cadastrar: {e.pgerror or e}")
    finally:
        conn.close()

    pausar()


# 4. EDITAR PRODUTO (UPDATE direto na tabela produto)

def editar_produto():
    cabecalho("EDITAR PRODUTO")

    try:
        id_produto = int(input("  ID do produto a editar: ").strip())
    except ValueError:
        print("\nID inválido.")
        pausar()
        return

    produto = buscar_por_id(id_produto)
    if not produto:
        print(f"\nProduto com ID {id_produto} não encontrado.")
        pausar()
        return

    print("\n  Dados atuais:")
    exibir_produto(produto)
    print("\n  Novos valores (Enter para manter o atual):\n")

    nova_descricao = input(f"  Descrição [{produto['descricao']}]: ").strip()
    nova_unidade   = input(f"  Unidade   [{produto['unidade']}]: ").strip().upper()
    novo_est_min_s = input(f"  Est. Mín  [{float(produto['estoque_minimo']):.2f}]: ").strip()

    descricao  = nova_descricao  or produto['descricao']
    unidade    = nova_unidade    or produto['unidade']
    try:
        estoque_minimo = float(novo_est_min_s) if novo_est_min_s else float(produto['estoque_minimo'])
    except ValueError:
        print("\nValor inválido para estoque mínimo.")
        pausar()
        return

    print()
    confirm = input("  Confirmar alterações? (s/n): ").strip().lower()
    if confirm != "s":
        print("  Operação cancelada.")
        pausar()
        return

    sql = """
        UPDATE produto
        SET descricao      = %s,
            unidade        = %s,
            estoque_minimo = %s
        WHERE id_produto   = %s
    """
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (descricao, unidade, estoque_minimo, id_produto))
        conn.commit()
        print("\nProduto atualizado com sucesso!")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"\nErro ao atualizar: {e.pgerror or e}")
    finally:
        conn.close()

    pausar()


# 5. EXCLUIR PRODUTO (Usa a trigger)

def excluir_produto():
    cabecalho("EXCLUIR PRODUTO")

    try:
        id_produto = int(input("  ID do produto a excluir: ").strip())
    except ValueError:
        print("\nID inválido.")
        pausar()
        return

    produto = buscar_por_id(id_produto)
    if not produto:
        print(f"\nProduto com ID {id_produto} não encontrado.")
        pausar()
        return

    print("\n  Produto selecionado:")
    exibir_produto(produto)
    print()

    if float(produto['estoque_atual']) > 0:
        print(f"Atenção: este produto possui "
              f"{float(produto['estoque_atual']):.2f} unidades em estoque.")
        print("     A TRIGGER do banco irá bloquear a exclusão.")

    confirm = input("\n  Confirmar exclusão? (s/n): ").strip().lower()
    if confirm != "s":
        print("  Operação cancelada.")
        pausar()
        return

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM produto WHERE id_produto = %s", (id_produto,))
        conn.commit()
        print("\nProduto excluído com sucesso!")
        print("     O registro de estoque foi removido automaticamente pela trigger.")
    except psycopg2.Error as e:
        conn.rollback()
        msg = e.pgerror or str(e)
        if "Não é permitido excluir" in msg:
            print(f"\nBloqueado pela trigger: {msg.strip()}")
        else:
            print(f"\nErro ao excluir: {msg}")
    finally:
        conn.close()

    pausar()


# MENU PRINCIPAL

def menu_busca():
    """Sub-opção de busca por descrição dentro da listagem."""
    cabecalho("BUSCAR PRODUTOS")
    termo = input("  Digite parte do nome do produto: ").strip()
    print()
    listar_produtos(busca=termo)
    pausar()


def menu_detalhe():
    """Exibe os detalhes completos de um produto pelo ID."""
    cabecalho("DETALHES DO PRODUTO")
    try:
        id_produto = int(input("  ID do produto: ").strip())
    except ValueError:
        print("\nID inválido.")
        pausar()
        return

    produto = buscar_por_id(id_produto)
    if produto:
        print()
        exibir_produto(produto)
    else:
        print(f"\nProduto com ID {id_produto} não encontrado.")
    pausar()


def main():
    opcoes = {
        "1": ("Listar todos os produtos",    lambda: (listar_produtos(), pausar())),
        "2": ("Buscar produto por descrição", menu_busca),
        "3": ("Ver detalhes de um produto",   menu_detalhe),
        "4": ("Cadastrar novo produto",        inserir_produto),
        "5": ("Editar produto",                editar_produto),
        "6": ("Excluir produto",               excluir_produto),
        "0": ("Sair",                          None),
    }

    while True:
        cabecalho("SISTEMA DE SUPRIMENTOS CRUD DE PRODUTOS")
        for chave, (descricao, _) in opcoes.items():
            print(f"  [{chave}] {descricao}")
        print()
        linha()
        escolha = input("  Opção: ").strip()

        if escolha == "0":
            limpar_tela()
            print("  Até logo!\n")
            break
        elif escolha in opcoes:
            _, acao = opcoes[escolha]
            if callable(acao):
                acao()
        else:
            print("\nOpção inválida.")
            pausar()


if __name__ == "__main__":
    main()


# COMO RODAR:

# pip install psycopg2-binary
# python crud_produto.py

# Configurando a conexão

# $env:DB_NAME="suprimentos"
# $env:DB_USER="postgres"
# $env:DB_PASS="sua_senha"