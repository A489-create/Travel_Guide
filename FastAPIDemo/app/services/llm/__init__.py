"""LLM / Embedding 抽象层包。

对外暴露工厂方法，业务层通过工厂获取具体实现：

    from app.services.llm.factory import LLMFactory, EmbeddingFactory

    llm = LLMFactory.get_llm()
    embedding = EmbeddingFactory.get_embedding()
"""
